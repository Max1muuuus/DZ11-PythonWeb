from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import EventFilterForm, EventForm, ProfileForm, RegistrationForm
from .models import Booking, Event


def event_list(request):
    form = EventFilterForm(request.GET or None)
    events = Event.objects.filter(status=Event.Status.PUBLISHED).annotate(
        popularity=Count("bookings", filter=Q(bookings__status=Booking.Status.ACTIVE))
    )
    if form.is_valid():
        filters = form.cleaned_data
        if filters["category"]:
            events = events.filter(category__icontains=filters["category"])
        if filters["date_from"]:
            events = events.filter(starts_at__date__gte=filters["date_from"])
        if filters["date_to"]:
            events = events.filter(starts_at__date__lte=filters["date_to"])
        if filters["min_price"] is not None:
            events = events.filter(price__gte=filters["min_price"])
        if filters["max_price"] is not None:
            events = events.filter(price__lte=filters["max_price"])
        if filters["sort"] == "popular":
            events = events.order_by("-popularity", "starts_at")
        elif filters["sort"] == "price":
            events = events.order_by("price", "starts_at")
    return render(request, "events/event_list.html", {"events": events, "form": form})


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.status == Event.Status.DRAFT and not (
        request.user.is_authenticated
        and (request.user.is_moderator or event.organizer_id == request.user.id)
    ):
        raise Http404
    booking = None
    if request.user.is_authenticated:
        booking = Booking.objects.filter(event=event, user=request.user).first()
    return render(
        request, "events/event_detail.html", {"event": event, "booking": booking}
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("events:event_list")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Реєстрацію успішно завершено.")
        return redirect("events:event_list")
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile(request):
    bookings = Booking.objects.filter(user=request.user).select_related("event")
    selected_status = request.GET.get("status", "")
    if selected_status == Booking.Status.CANCELLED:
        bookings = bookings.filter(
            Q(status=Booking.Status.CANCELLED)
            | Q(event__status=Event.Status.CANCELLED)
        )
    elif selected_status in (Booking.Status.COMPLETED, Booking.Status.ACTIVE):
        desired_label = Booking.Status(selected_status).label
        bookings = [
            booking for booking in bookings if booking.display_status == desired_label
        ]
    return render(
        request,
        "events/profile.html",
        {"bookings": bookings, "selected_status": selected_status},
    )


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профіль оновлено.")
        return redirect("events:profile")
    return render(request, "events/profile_edit.html", {"form": form})


@login_required
@require_POST
def book_event(request, pk):
    try:
        with transaction.atomic():
            event = get_object_or_404(Event.objects.select_for_update(), pk=pk)
            if event.organizer_id == request.user.id:
                messages.error(request, "Організатор не може бронювати власний захід.")
            elif event.status == Event.Status.CANCELLED:
                messages.error(request, "Не можна бронювати скасований захід.")
            elif event.status != Event.Status.PUBLISHED:
                messages.error(request, "Бронювати можна лише опубліковані заходи.")
            elif event.status == Event.Status.COMPLETED or event.is_over:
                messages.error(request, "Не можна бронювати завершений захід.")
            elif event.starts_at <= timezone.now():
                messages.error(request, "Не можна бронювати захід, який уже розпочався.")
            elif Booking.objects.filter(event=event, user=request.user).exists():
                messages.error(request, "Ви вже бронювали цей захід.")
            elif event.active_booking_count >= event.capacity:
                messages.error(request, "На цей захід більше немає вільних місць.")
            else:
                Booking.objects.create(event=event, user=request.user)
                messages.success(request, "Місце на захід успішно заброньовано.")
    except IntegrityError:
        messages.error(request, "Ви вже бронювали цей захід.")
    return redirect("events:event_detail", pk=pk)


@login_required
@require_POST
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status != Booking.Status.ACTIVE or booking.event.status == Event.Status.CANCELLED:
        messages.error(request, "Це бронювання вже не є активним.")
    elif booking.event.starts_at <= timezone.now():
        messages.error(request, "Скасувати бронювання після початку заходу не можна.")
    else:
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=("status",))
        messages.success(request, "Бронювання скасовано.")
    return redirect("events:profile")


def _can_manage_events(user):
    return user.is_authenticated and user.can_manage_events


@login_required
def organizer_events(request):
    if not _can_manage_events(request.user):
        messages.error(request, "Недостатньо прав для керування заходами.")
        return redirect("events:event_list")
    events = Event.objects.all()
    if not request.user.is_moderator:
        events = events.filter(organizer=request.user)
    return render(request, "events/organizer_events.html", {"events": events})


@login_required
def event_create(request):
    if not _can_manage_events(request.user):
        messages.error(request, "Створювати заходи можуть лише організатори.")
        return redirect("events:event_list")
    form = EventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        event.organizer = request.user
        event.save()
        messages.success(request, "Захід створено.")
        return redirect("events:organizer_events")
    return render(request, "events/event_form.html", {"form": form, "title": "Новий захід"})


@login_required
def event_edit(request, pk):
    if not _can_manage_events(request.user):
        messages.error(request, "Недостатньо прав для редагування заходу.")
        return redirect("events:event_list")
    event = get_object_or_404(Event, pk=pk)
    if not request.user.is_moderator and event.organizer_id != request.user.id:
        messages.error(request, "Ви можете редагувати лише власні заходи.")
        return redirect("events:organizer_events")
    form = EventForm(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Захід оновлено.")
        return redirect("events:organizer_events")
    return render(request, "events/event_form.html", {"form": form, "title": "Редагувати захід"})


@login_required
@require_POST
def event_delete(request, pk):
    if not _can_manage_events(request.user):
        messages.error(request, "Недостатньо прав для видалення заходу.")
        return redirect("events:event_list")
    event = get_object_or_404(Event, pk=pk)
    if not request.user.is_moderator and event.organizer_id != request.user.id:
        messages.error(request, "Ви можете видаляти лише власні заходи.")
        return redirect("events:organizer_events")
    event.delete()
    messages.success(request, "Захід видалено.")
    return redirect("events:organizer_events")
