from django.db.models.signals import pre_save
from django.dispatch import receiver

@receiver(pre_save, sender=None)
def order_status_change(sender, instance, **kwargs):
    from products.models import OrderDetails, Notification

    if not isinstance(instance, OrderDetails):
        return

    if not instance.pk:
        return

    previous = OrderDetails.objects.get(pk=instance.pk)

    if previous.status != instance.status:
        Notification.objects.create(
            customer=instance.customer,
            order=instance,
            type=Notification.NotificationType.ORDER_STATUS,
            title="Order Status Updated",
            message=f"Your order {instance.order_number} is now '{instance.status}'."
        )
