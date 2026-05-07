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
  currentLocation: {
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
  status: { type: String, enum: ['available', 'busy'], default: 'available', index: true },
  socketId: String, // Store current socket ID when connected
});

driverSchema.index({ currentLocation: '2dsphere' });

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
  notifiedDriverIds: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Driver' }],
});

const Driver = mongoose.model('Driver', driverSchema);
const Ride = mongoose.model('Ride', rideSchema);

// --- Dummy Data Seeder ---
const seedDrivers = async () => {
  await Driver.deleteMany({});
  // Dummy location: Nashik center roughly [73.7898, 19.9975]
  const drivers = [
    { name: 'Driver A', currentLocation: { type: 'Point', coordinates: [73.7898, 19.9975] } }, // Very close
    { name: 'Driver B', currentLocation: { type: 'Point', coordinates: [73.7900, 19.9980] } }, // Close
    { name: 'Driver C', currentLocation: { type: 'Point', coordinates: [73.8500, 20.0500] } }, // Far > 5km
  ];
  const seeded = await Driver.insertMany(drivers);
  console.log('Seeded drivers:', seeded.map((d) => ({ id: String(d._id), name: d.name })));
};

// Demo-only helper to fetch seeded drivers for driver app registration.
app.get('/drivers', async (_req, res) => {
  const drivers = await Driver.find({}).select('_id name status currentLocation');
  res.json(drivers);
});

// --- Socket.io Logic ---
io.on('connection', (socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Driver registers their socket connection
  socket.on('registerDriver', async (driverId, ack) => {
    try {
      const driver = await Driver.findByIdAndUpdate(
        driverId,
        { socketId: socket.id, status: 'available' },
        { new: true }
      );
      if (!driver) {
        ack?.({ ok: false, message: 'Driver not found' });
        return;
      }
      socket.join(`driver:${String(driver._id)}`);
      console.log(`Driver ${driverId} registered with socket ${socket.id}`);
      ack?.({ ok: true, driverId: String(driver._id), name: driver.name });
    } catch (err) {
      console.error('Error registering driver:', err);
      ack?.({ ok: false, message: 'Driver registration failed' });
    }
  });

  // Customer books a ride
  socket.on('bookRide', async (data, ack) => {
    console.log('Ride requested by customer:', data);
    try {
      // 1. Save pending ride
      const newRide = new Ride({
        customerId: data.customerId || 'customer_1',
        customerSocketId: socket.id,
        pickup: { type: 'Point', coordinates: data.pickup },
        destination: { type: 'Point', coordinates: data.destination },
        fare: data.fare,
        status: 'pending',
      });
      await newRide.save();

      // 2. Proximity Search: For local UI testing, widen radius so cross-city
      // bookings still produce a driver popup reliably.
      const maxDistance = 250000; // 250 km in meters
      let nearbyDrivers = await Driver.find({
        status: 'available',
        socketId: { $exists: true, $ne: null }, // Must be online
        currentLocation: {
          $nearSphere: {
            $geometry: {
              type: 'Point',
              coordinates: data.pickup, // [longitude, latitude]
            },
            $maxDistance: maxDistance,
          },
        },
      });

      // Fallback for demo reliability: if geo match is empty, notify any online driver.
      if (nearbyDrivers.length === 0) {
        nearbyDrivers = await Driver.find({
          status: 'available',
          socketId: { $exists: true, $ne: null }
        });
      }

      console.log(`Found ${nearbyDrivers.length} nearby drivers.`);

      // 3. Real-Time Notification to nearby drivers
      if (nearbyDrivers.length === 0) {
        socket.emit('noDriversAvailable', { message: 'No drivers found nearby.' });
        ack?.({ ok: true, rideId: String(newRide._id), notifiedCount: 0 });
        return;
      }

      const rideData = {
        rideId: newRide._id,
        bookingId: data.bookingId || data.booking_id,
        booking_id: data.booking_id || data.bookingId,
        pickup: data.pickup,
        destination: data.destination,
        pickupAddressText: data.pickupAddressText,
        dropAddressText: data.dropAddressText,
        fare: data.fare,
        customerName: data.customer_name ?? data.customerName,
        customerPhone: data.customer_phone ?? data.customerPhone,
        notes: data.notes,
      };

      const notifiedIds = [];
      nearbyDrivers.forEach(driver => {
        notifiedIds.push(driver._id);
        io.to(driver.socketId).emit('rideRequest', rideData);
      });

      newRide.notifiedDriverIds = notifiedIds;
      await newRide.save();
      ack?.({ ok: true, rideId: String(newRide._id), notifiedCount: nearbyDrivers.length });
    } catch (err) {
      console.error('Error in bookRide:', err);
      socket.emit('rideError', { message: 'Failed to request ride.' });
      ack?.({ ok: false, message: 'Failed to request ride.' });
    }
  });

  // Driver accepts a ride
  socket.on('acceptRide', async (data, ack) => {
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
        ack?.({ ok: false, message: 'Ride is no longer available.' });
        return;
      }

      // Keep demo driver available so repeated Confirm-and-Book tests continue
      // showing offer notifications without manual reset between attempts.
      await Driver.findByIdAndUpdate(data.driverId, { status: 'available' });

      // Notify the customer
      io.to(ride.customerSocketId).emit('rideAccepted', { driverId: data.driverId });

      // Notify only drivers who were originally notified for this ride.
      (ride.notifiedDriverIds || []).forEach((notifiedDriverId) => {
        if (String(notifiedDriverId) === String(data.driverId)) return;
        io.to(`driver:${String(notifiedDriverId)}`).emit('rideNoLongerAvailable', { rideId: String(ride._id) });
      });
      
      // Notify the accepted driver of success
      socket.emit('acceptSuccess', { rideId: ride._id });
      ack?.({ ok: true, rideId: String(ride._id) });

    } catch (err) {
      console.error('Error in acceptRide:', err);
      ack?.({ ok: false, message: 'Failed to accept ride.' });
    }
  });

  socket.on('rejectRide', (_data, ack) => {
    ack?.({ ok: true });
  });

  socket.on('disconnect', async () => {
    console.log(`Client disconnected: ${socket.id}`);
    // Optional: unset driver socketId
    await Driver.findOneAndUpdate(
      { socketId: socket.id },
      { $unset: { socketId: "" }, status: 'available' }
    );
  });
});

const PORT = process.env.PORT || 4000;
server.listen(PORT, async () => {
  await connectDB();
  console.log(`Ride real-time backend running on port ${PORT}`);
});
