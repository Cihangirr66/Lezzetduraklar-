# -*- coding: utf-8 -*-
from django.http import JsonResponse

from .firebase import get_firebase_app


def firebase_status(request):
    try:
        app = get_firebase_app()
    except Exception as exc:
        return JsonResponse(
            {
                'connected': False,
                'error': str(exc),
            },
            status=503,
        )

    return JsonResponse(
        {
            'connected': True,
            'name': app.name,
            'project_id': app.project_id,
        }
    )
