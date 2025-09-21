from rest_framework import serializers
from .models import Auth,AdminDetails,CustomerDetails
from django.contrib.auth.hashers import check_password

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            user = Auth.objects.get(email=data['email'])
        except Auth.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password")

        if not check_password(data['password'], user.password):
            raise serializers.ValidationError("Invalid email or password")

        data['user'] = user
        return data


class AdminDetailsSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='auth.email', read_only=True)
    class Meta:
        model = AdminDetails  
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerDetails
        fields = "__all__"