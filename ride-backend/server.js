const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const mongoose = require('mongoose');
const cors = require('cors');
const { MongoMemoryServer } = require('mongodb-memory-server');

const app = express();
app.use(cors());
app.use(express.json());

const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST'],
  },
});

// --- MongoDB Setup ---
let mongoServer;
const connectDB = async () => {
  try {
    mongoServer = await MongoMemoryServer.create();
    const uri = mongoServer.getUri();
    await mongoose.connect(uri);
    console.log(`Connected to in-memory MongoDB at ${uri}`);
    await seedDrivers();
  } catch (error) {
    console.error('MongoDB connection error:', error);
    process.exit(1);
  }
};

// --- Schemas ---
const driverSchema = new mongoose.Schema({
  name: String,
  location: {
    type: {
      type: String,
      enum: ['Point'],
      required: true,
    },
    coordinates: {
      type: [Number], // [longitude, latitude]
      required: true,
    },
  },
  status: { type: String, enum: ['available', 'busy'], default: 'available' },
  socketId: String, // Store current socket ID when connected
});

driverSchema.index({ location: '2dsphere' });

const rideSchema = new mongoose.Schema({
  customerId: String,
  customerSocketId: String,
  pickup: {
    type: { type: String, enum: ['Point'], default: 'Point' },
    coordinates: [Number],
  },
  destination: {
    type: { type: String, enum: ['Point'], default: 'Point' },
    coordinates: [Number],
  },
  fare: Number,
  status: { type: String, enum: ['pending', 'accepted', 'completed', 'cancelled'], default: 'pending' },
  driverId: { type: mongoose.Schema.Types.ObjectId, ref: 'Driver' },
});

const Driver = mongoose.model('Driver', driverSchema);
const Ride = mongoose.model('Ride', rideSchema);

// --- Dummy Data Seeder ---
const seedDrivers = async () => {
  await Driver.deleteMany({});
  // Dummy location: Nashik center roughly [73.7898, 19.9975]
  const drivers = [
    { name: 'Driver A', location: { type: 'Point', coordinates: [73.7898, 19.9975] } }, // Very close
    { name: 'Driver B', location: { type: 'Point', coordinates: [73.7900, 19.9980] } }, // Close
    { name: 'Driver C', location: { type: 'Point', coordinates: [73.8500, 20.0500] } }, // Far > 5km
  ];
  await Driver.insertMany(drivers);
  console.log('Seeded 3 dummy drivers.');
};

// --- Socket.io Logic ---
io.on('connection', (socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Driver registers their socket connection
  socket.on('registerDriver', async (driverId) => {
    try {
      await Driver.findByIdAndUpdate(driverId, { socketId: socket.id });
      console.log(`Driver ${driverId} registered with socket ${socket.id}`);
    } catch (err) {
      console.error('Error registering driver:', err);
    }
  });

  // Customer books a ride
  socket.on('bookRide', async (data) => {
    console.log('Ride requested by customer:', data);
    try {
      // 1. Save pending ride
      const newRide = new Ride({
        customerId: data.customerId || 'customer_1',
        customerSocketId: socket.id,
        pickup: { coordinates: data.pickup },
        destination: { coordinates: data.destination },
        fare: data.fare,
        status: 'pending',
      });
      await newRide.save();

      // 2. Proximity Search: Find available drivers within 5km of pickup point
      const maxDistance = 5000; // 5 kilometers in meters
      const nearbyDrivers = await Driver.find({
        status: 'available',
        socketId: { $exists: true, $ne: null }, // Must be online
        location: {
          $nearSphere: {
            $geometry: {
              type: 'Point',
              coordinates: data.pickup, // [longitude, latitude]
            },
            $maxDistance: maxDistance,
          },
        },
      });

      console.log(`Found ${nearbyDrivers.length} nearby drivers.`);

      // 3. Real-Time Notification to nearby drivers
      if (nearbyDrivers.length === 0) {
        socket.emit('noDriversAvailable', { message: 'No drivers found nearby.' });
        return;
      }

      const rideData = {
        rideId: newRide._id,
        pickup: data.pickup,
        destination: data.destination,
        fare: data.fare,
      };

      nearbyDrivers.forEach(driver => {
        io.to(driver.socketId).emit('rideRequest', rideData);
      });

    } catch (err) {
      console.error('Error in bookRide:', err);
      socket.emit('rideError', { message: 'Failed to request ride.' });
    }
  });

  // Driver accepts a ride
  socket.on('acceptRide', async (data) => {
    console.log(`Driver ${data.driverId} attempting to accept ride ${data.rideId}`);
    try {
      // Concurrency Handling: find and update ONLY if still pending
      const ride = await Ride.findOneAndUpdate(
        { _id: data.rideId, status: 'pending' },
        { status: 'accepted', driverId: data.driverId },
        { new: true }
      );

      if (!ride) {
        // Ride was already accepted or cancelled
        socket.emit('rideUnavailable', { message: 'Ride is no longer available.' });
        return;
      }

      // Update driver status
      await Driver.findByIdAndUpdate(data.driverId, { status: 'busy' });

      // Notify the customer
      io.to(ride.customerSocketId).emit('rideAccepted', { driverId: data.driverId });

      // Notify all OTHER drivers to remove the popup (broadcasting to everyone, they can check if rideId matches)
      // Alternatively, we could query the nearby drivers again or broadcast globally.
      socket.broadcast.emit('rideNoLongerAvailable', { rideId: ride._id });
      
      // Notify the accepted driver of success
      socket.emit('acceptSuccess', { rideId: ride._id });

    } catch (err) {
      console.error('Error in acceptRide:', err);
    }
  });

  socket.on('disconnect', async () => {
    console.log(`Client disconnected: ${socket.id}`);
    // Optional: unset driver socketId
    await Driver.findOneAndUpdate({ socketId: socket.id }, { $unset: { socketId: "" } });
  });
});

const PORT = process.env.PORT || 4000;
server.listen(PORT, async () => {
  await connectDB();
  console.log(`Ride real-time backend running on port ${PORT}`);
});
