from django.urls import path
from . import views
from .views import create_upgrade_view

app_name = 'main'

urlpatterns = [
    path('', views.cases_list, name='cases_list'),
    path('search/', views.cases_search, name='cases_search'),
    path('filter_search/', views.cases_filter_search, name='cases_filter_search'),
    path('case/<slug:slug>/spin/', views.spin_case, name='spin_case'),
    path('case/<slug:slug>/', views.case_detail, name='case_detail'),
    path('profile/', views.profile_view, name='profile'),
    path('update_trade_url/', views.update_trade_url_view, name='update_trade_url'),
    path('buy-for/', views.buy_for_item_view, name='buy_for_item'),
    path('sell/', views.sell_items, name='sell_items'),
    path('logout/', views.logout_view, name='logout'),
    path('upgrades/', views.upgrades_view, name='upgrades'),
    path('create_upgrade/', create_upgrade_view, name='create_upgrade'),
    path('contracts/', views.contracts_view, name='contracts'),
    path('contracts/create/', views.create_contract_view, name='create_contract'),
    path("poll-withdrawals/", views.poll_withdrawals_view, name="poll-withdrawals-url"),
    path('api/targets/', views.load_targets, name='load_targets'),
    path("deposit/", views.deposit_view, name="add_balance"),
]
