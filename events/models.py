from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "user", "Користувач"
        ADMIN = "admin", "Організатор"
        MODERATOR = "moderator", "Модератор"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)

    def save(self, *args, **kwargs):
        if not self.is_superuser:
            self.is_staff = self.role == self.Role.MODERATOR
        super().save(*args, **kwargs)

    def has_perm(self, perm, obj=None):
        return self.is_moderator or super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        return self.is_moderator or super().has_module_perms(app_label)

    @property
    def can_manage_events(self):
        return self.role in (self.Role.ADMIN, self.Role.MODERATOR) or self.is_superuser

    @property
    def is_moderator(self):
        return self.role == self.Role.MODERATOR or self.is_superuser


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Чернетка"
        PUBLISHED = "published", "Опубліковано"
        CANCELLED = "cancelled", "Скасовано"
        COMPLETED = "completed", "Завершено"

    title = models.CharField("Назва", max_length=200)
    description = models.TextField("Опис")
    category = models.CharField("Категорія", max_length=80)
    location = models.CharField("Місце проведення", max_length=200)
    starts_at = models.DateTimeField("Початок")
    ends_at = models.DateTimeField("Завершення", null=True, blank=True)
    price = models.DecimalField("Ціна", max_digits=10, decimal_places=2, default=0)
    capacity = models.PositiveIntegerField("Кількість місць")
    status = models.CharField(
        "Статус", max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organized_events",
        verbose_name="Організатор",
    )
    created_at = models.DateTimeField("Створено", auto_now_add=True)

    class Meta:
        ordering = ("starts_at",)

    def __str__(self):
        return self.title

    @property
    def is_over(self):
        end_time = self.ends_at or self.starts_at
        return end_time <= timezone.now()

    @property
    def active_booking_count(self):
        return self.bookings.filter(status=Booking.Status.ACTIVE).count()

    @property
    def available_seats(self):
        return max(self.capacity - self.active_booking_count, 0)


class Booking(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активне"
        CANCELLED = "cancelled", "Скасоване"
        COMPLETED = "completed", "Завершене"

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="bookings", verbose_name="Захід"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name="Користувач",
    )
    status = models.CharField(
        "Статус", max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    booked_at = models.DateTimeField("Заброньовано", auto_now_add=True)

    class Meta:
        ordering = ("-booked_at",)
        constraints = [
            models.UniqueConstraint(fields=("event", "user"), name="unique_event_booking")
        ]

    def __str__(self):
        return f"{self.user} — {self.event}"

    @property
    def display_status(self):
        if self.status == self.Status.CANCELLED or self.event.status == Event.Status.CANCELLED:
            return self.Status.CANCELLED.label
        if self.status == self.Status.COMPLETED or self.event.is_over:
            return self.Status.COMPLETED.label
        return self.Status.ACTIVE.label
