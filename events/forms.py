from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Event, User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Електронна пошта")
    first_name = forms.CharField(label="Ім'я", max_length=150)
    last_name = forms.CharField(label="Прізвище", max_length=150)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {"username": "Ім'я користувача"}


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "Ім'я",
            "last_name": "Прізвище",
            "email": "Електронна пошта",
        }


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = (
            "title",
            "description",
            "category",
            "location",
            "starts_at",
            "ends_at",
            "price",
            "capacity",
            "status",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "ends_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "description": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "title": "Назва",
            "description": "Опис",
            "category": "Категорія",
            "location": "Місце проведення",
            "starts_at": "Дата й час початку",
            "ends_at": "Дата й час завершення",
            "price": "Ціна",
            "capacity": "Кількість місць",
            "status": "Статус",
        }

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get("starts_at")
        ends_at = cleaned_data.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", "Завершення має бути пізніше за початок.")
        return cleaned_data


class EventFilterForm(forms.Form):
    category = forms.CharField(label="Категорія", required=False)
    date_from = forms.DateField(
        label="З дати", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        label="До дати", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    min_price = forms.DecimalField(label="Ціна від", required=False, min_value=0)
    max_price = forms.DecimalField(label="Ціна до", required=False, min_value=0)
    sort = forms.ChoiceField(
        label="Сортування",
        required=False,
        choices=(("", "За датою"), ("popular", "За популярністю"), ("price", "За ціною")),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_to < date_from:
            self.add_error("date_to", "Кінцева дата має бути не раніше початкової.")
        min_price = cleaned_data.get("min_price")
        max_price = cleaned_data.get("max_price")
        if min_price is not None and max_price is not None and max_price < min_price:
            self.add_error("max_price", "Максимальна ціна має бути не меншою за мінімальну.")
        return cleaned_data
