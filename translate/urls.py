from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("unlock/", views.unlock, name="unlock"),
    path("history/", views.history, name="history"),
    path("t/<int:pk>/", views.detail, name="detail"),
    path("t/<int:pk>/reuse/", views.reuse, name="reuse"),
    path("t/<int:pk>/delete/", views.delete, name="delete"),
]
