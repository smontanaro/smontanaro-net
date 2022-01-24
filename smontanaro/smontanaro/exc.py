
"Handler for non-standard NGINX 444 response code"

import werkzeug.exceptions

class NoResponse(werkzeug.exceptions.HTTPException):
    "see __doc__"
    code = 444
    description = "No Response"

def init_app(app):
    "see __doc__"

    @app.errorhandler(werkzeug.exceptions.BadRequest)
    def handle_444(_exc):
        "see __doc__"
        return "No Response", 444

    app.register_error_handler(NoResponse, handle_444)
