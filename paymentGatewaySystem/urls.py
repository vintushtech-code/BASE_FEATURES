from django.urls import path
from paymentGatewaySystem import views

app_name = 'paymentGatewaySystem'

urlpatterns = [
    path('ui/', views.DashboardView.as_view(), name='dashboard-ui'),
    path('list/', views.ListTransactionsView.as_view(), name='list-transactions'),
    path('create-order/', views.CreateOrderView.as_view(), name='create-order'),
    path('tokenize-card/', views.TokenizeCardView.as_view(), name='tokenize-card'),
    path('process-token-payment/', views.ProcessTokenPaymentView.as_view(), name='process-token-payment'),
    path('refund/', views.RefundView.as_view(), name='refund'),
    path('webhook/', views.WebhookView.as_view(), name='webhook'),
    path('status/<uuid:transaction_id>/', views.TransactionStatusView.as_view(), name='transaction-status'),
    path('reconcile/', views.RunReconciliationView.as_view(), name='reconcile'),
    path('poll-pending/', views.PollPendingPaymentsView.as_view(), name='poll-pending'),
]

