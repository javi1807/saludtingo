from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages

def is_farmacia_staff(user):
    return user.is_superuser or user.groups.filter(name='Farmacia_Staff').exists()

def is_urgencias_staff(user):
    return user.is_superuser or user.groups.filter(name='Urgencias_Staff').exists()

def login_view(request):
    if request.user.is_authenticated:
        if is_farmacia_staff(request.user) and not request.user.is_superuser:
            return redirect('/farmacia/dashboard/')
        return redirect('/')

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            auth_login(request, user)
            if is_farmacia_staff(user) and not request.user.is_superuser:
                return redirect('/farmacia/dashboard/')
            return redirect('/')
        else:
            messages.error(request, 'Credenciales incorrectas.')
            
    return render(request, 'login.html')

def logout_view(request):
    auth_logout(request)
    return redirect('login')
