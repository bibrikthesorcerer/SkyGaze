from django.urls import path
from mainApp import views

urlpatterns = [
			   path('', views.index), # http://127.0.0.1:8000/
               path('session/', views.session),
               path('constellations/', views.constells),
               path('wiki/<str:suffix>', views.wiki_redirect),
               path('api/get_wiki_page/', views.get_wiki_page),
               path('api/get_by_id/', views.get_by_id),
]