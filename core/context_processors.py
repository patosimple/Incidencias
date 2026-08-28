from django.conf import settings


def modo_filtro_cliente(request):
    return {
        "MODO_FILTRO_CLIENTE": getattr(settings, "MODO_FILTRO_CLIENTE", False),
    }
