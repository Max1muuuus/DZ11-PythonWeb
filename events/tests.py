from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Event, User


class EventPlatformTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="attendee", password="Strong-test-pass-27"
        )
        self.organizer = User.objects.create_user(
            username="organizer",
            password="Strong-test-pass-27",
            role=User.Role.ADMIN,
        )
        self.event = Event.objects.create(
            title="Python Meetup",
            description="A community event",
            category="Technology",
            location="Kyiv",
            starts_at=timezone.now() + timedelta(days=4),
            price=Decimal("100.00"),
            capacity=2,
            status=Event.Status.PUBLISHED,
            organizer=self.organizer,
        )

    def test_booking_can_be_created_only_once(self):
        self.client.force_login(self.user)
        url = reverse("events:book_event", args=(self.event.pk,))

        self.client.post(url)
        self.client.post(url)

        self.assertEqual(
            Booking.objects.filter(event=self.event, user=self.user).count(), 1
        )

    def test_organizer_cannot_book_own_event(self):
        self.client.force_login(self.organizer)

        self.client.post(reverse("events:book_event", args=(self.event.pk,)))

        self.assertFalse(Booking.objects.filter(event=self.event).exists())

    def test_cancelled_completed_and_started_events_cannot_be_booked(self):
        cases = (
            {"status": Event.Status.CANCELLED},
            {"status": Event.Status.COMPLETED},
            {"starts_at": timezone.now() - timedelta(minutes=5)},
        )
        self.client.force_login(self.user)
        for index, changes in enumerate(cases):
            with self.subTest(changes=changes):
                event_data = {
                    "title": f"Unavailable {index}",
                    "description": "Test event",
                    "category": "Test",
                    "location": "Kyiv",
                    "starts_at": timezone.now() + timedelta(days=3),
                    "price": Decimal("0"),
                    "capacity": 5,
                    "status": Event.Status.PUBLISHED,
                    "organizer": self.organizer,
                }
                event_data.update(changes)
                event = Event.objects.create(**event_data)
                self.client.post(reverse("events:book_event", args=(event.pk,)))
                self.assertFalse(Booking.objects.filter(event=event).exists())

    def test_booking_respects_capacity(self):
        Booking.objects.create(
            event=self.event,
            user=User.objects.create_user(
                username="attendee2", password="Strong-test-pass-27"
            ),
        )
        Booking.objects.create(
            event=self.event,
            user=User.objects.create_user(
                username="attendee3", password="Strong-test-pass-27"
            ),
        )
        self.client.force_login(self.user)

        self.client.post(reverse("events:book_event", args=(self.event.pk,)))

        self.assertFalse(Booking.objects.filter(event=self.event, user=self.user).exists())

    def test_cancelled_booking_cannot_be_booked_twice(self):
        booking = Booking.objects.create(event=self.event, user=self.user)
        self.client.force_login(self.user)

        self.client.post(reverse("events:cancel_booking", args=(booking.pk,)))

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.client.post(reverse("events:book_event", args=(self.event.pk,)))
        self.assertEqual(
            Booking.objects.filter(event=self.event, user=self.user).count(), 1
        )

    def test_event_filters_by_category_price_and_popularity(self):
        cheaper = Event.objects.create(
            title="Design Forum",
            description="Design",
            category="Design",
            location="Lviv",
            starts_at=timezone.now() + timedelta(days=2),
            price=Decimal("20.00"),
            capacity=10,
            status=Event.Status.PUBLISHED,
            organizer=self.organizer,
        )
        Booking.objects.create(event=self.event, user=self.user)
        response = self.client.get(
            reverse("events:event_list"),
            {"category": "tech", "min_price": "50", "sort": "popular"},
        )

        self.assertContains(response, self.event.title)
        self.assertNotContains(response, cheaper.title)

    def test_event_list_filters_by_date_and_sorts_by_popularity_and_price(self):
        less_popular = Event.objects.create(
            title="Less Popular Meetup",
            description="Technology",
            category="Technology",
            location="Lviv",
            starts_at=timezone.now() + timedelta(days=2),
            price=Decimal("50.00"),
            capacity=10,
            status=Event.Status.PUBLISHED,
            organizer=self.organizer,
        )
        popular_user = User.objects.create_user(
            username="popular-attendee", password="Strong-test-pass-27"
        )
        Booking.objects.create(event=self.event, user=self.user)
        Booking.objects.create(event=less_popular, user=popular_user)
        Booking.objects.create(
            event=less_popular,
            user=User.objects.create_user(
                username="another-popular-attendee", password="Strong-test-pass-27"
            ),
        )

        popular_response = self.client.get(
            reverse("events:event_list"), {"sort": "popular"}
        )
        price_response = self.client.get(
            reverse("events:event_list"), {"sort": "price"}
        )
        date_response = self.client.get(
            reverse("events:event_list"),
            {
                "date_from": self.event.starts_at.date().isoformat(),
                "date_to": self.event.starts_at.date().isoformat(),
            },
        )

        self.assertEqual(
            list(popular_response.context["events"][:2]),
            [less_popular, self.event],
        )
        self.assertEqual(
            list(price_response.context["events"][:2]),
            [less_popular, self.event],
        )
        self.assertEqual(list(date_response.context["events"]), [self.event])

    def test_registration_creates_a_regular_user(self):
        response = self.client.post(
            reverse("events:register"),
            {
                "username": "new-user",
                "first_name": "New",
                "last_name": "Attendee",
                "email": "new@example.com",
                "password1": "Uncommon-password-942",
                "password2": "Uncommon-password-942",
            },
        )

        self.assertRedirects(response, reverse("events:event_list"))
        user = User.objects.get(username="new-user")
        self.assertEqual(user.role, User.Role.USER)
        self.assertFalse(user.is_staff)

    def test_moderator_can_access_django_admin(self):
        moderator = User.objects.create_user(
            username="moderator",
            password="Strong-test-pass-27",
            role=User.Role.MODERATOR,
        )
        self.client.force_login(moderator)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)

    def test_cancelled_event_appears_as_cancelled_in_booking_history(self):
        booking = Booking.objects.create(event=self.event, user=self.user)
        self.event.status = Event.Status.CANCELLED
        self.event.save(update_fields=("status",))
        self.client.force_login(self.user)

        response = self.client.get(reverse("events:profile"), {"status": "cancelled"})

        self.assertContains(response, self.event.title)
        self.assertContains(response, "Скасоване")
        self.assertEqual(booking.display_status, Booking.Status.CANCELLED.label)
