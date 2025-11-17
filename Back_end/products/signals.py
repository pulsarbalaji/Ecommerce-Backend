from django.db.models.signals import pre_save
from django.dispatch import receiver
from products.models import OrderDetails, Notification

def clean_label(text: str) -> str:
    """Convert snake_case to 'Title Case' with spaces."""
    return text.replace("_", " ").title()

@receiver(pre_save, sender=OrderDetails)
def order_status_change(sender, instance, **kwargs):

    # If new order, skip
    if not instance.pk:
        return

    previous = OrderDetails.objects.get(pk=instance.pk)

    # Only run when status actually changed
    if previous.status != instance.status:

        # 1️⃣ Create normal status update notification
        status_clean = clean_label(instance.status)
        Notification.objects.create(
            customer=instance.customer,
            order=instance,
            type=Notification.NotificationType.ORDER_STATUS,
            title="Order Status Updated",
            message=f"Your order {instance.order_number} is now '{status_clean}'."
        )

        # 2️⃣ If delivered → create product rating notifications
        if instance.status == OrderDetails.OrderStatus.DELIVERED:
            for item in instance.items.all():  # fetch all products in order
                product_name_clean = clean_label(item.product.product_name)
                Notification.objects.create(
                    customer=instance.customer,
                    order=instance,
                    product=item.product,
                    type=Notification.NotificationType.PRODUCT_RATING,
                    title="Rate Your Product",
                    message=f"Please rate your experience with '{product_name_clean}'."
                )
