from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Booking, Event, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Роль платформи", {"fields": ("role",)}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Роль платформи", {"fields": ("role",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_active")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "starts_at", "status", "organizer")
    list_filter = ("status", "category", "starts_at")
    search_fields = ("title", "description", "location", "organizer__username")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "status", "booked_at")
    list_filter = ("status", "booked_at")
    search_fields = ("event__title", "user__username", "user__email")
