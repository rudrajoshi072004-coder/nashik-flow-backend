from django.contrib import admin

from .models import FareRule


@admin.register(FareRule)
class FareRuleAdmin(admin.ModelAdmin):
    list_display = ("pricing_rule", "rule_type", "amount", "percentage", "active")
    list_filter = ("rule_type", "active")
    search_fields = ("pricing_rule__name", "rule_type")
