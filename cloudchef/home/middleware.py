class NoStoreForDynamicPagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        vary = response.get("Vary", "")
        vary_parts = [part.strip() for part in vary.split(",") if part.strip()]
        if "Cookie" not in vary_parts:
            vary_parts.append("Cookie")
        response["Vary"] = ", ".join(vary_parts)
        return response
