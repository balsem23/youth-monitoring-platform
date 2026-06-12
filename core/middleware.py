import time
import uuid
import logging
from django.utils.deprecation import MiddlewareMixin
from core.permissions import get_user_role

logger = logging.getLogger('django.request')

class RequestLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()
        request.correlation_id = str(uuid.uuid4())[:8]

    def process_response(self, request, response):
        start_time = getattr(request, 'start_time', None)
        duration = (time.time() - start_time) * 1000 if start_time else 0.0

        user = request.user
        username = user.username if user and user.is_authenticated else "Anonymous"
        role = get_user_role(user) if user and user.is_authenticated else "None"
        path = request.path
        method = request.method
        status_code = response.status_code
        correlation_id = getattr(request, 'correlation_id', 'N/A')

        logger.info(
            f"correlation_id={correlation_id} method={method} path={path} "
            f"status={status_code} user={username} role={role} duration={duration:.2f}ms"
        )
        return response
