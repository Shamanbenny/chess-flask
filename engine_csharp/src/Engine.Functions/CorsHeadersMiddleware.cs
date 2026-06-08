namespace Engine.Functions;

public static class CorsHeadersMiddleware
{
    private static readonly HashSet<string> AllowedOrigins = new(StringComparer.OrdinalIgnoreCase)
    {
        "https://sneakyowl.net",
        "https://www.sneakyowl.net",
    };

    public static IApplicationBuilder UseCorsHeaders(this IApplicationBuilder app)
    {
        return app.Use(async (context, next) =>
        {
            if (context.Request.Headers.TryGetValue("Origin", out var originValues))
            {
                var origin = originValues.FirstOrDefault();
                if (origin is not null && AllowedOrigins.Contains(origin))
                {
                    context.Response.Headers["Access-Control-Allow-Origin"] = origin;
                    context.Response.Headers["Access-Control-Allow-Credentials"] = "false";
                }
            }

            context.Response.Headers["Access-Control-Allow-Methods"] = "POST, OPTIONS";
            context.Response.Headers["Access-Control-Allow-Headers"] = "Content-Type";

            await next();
        });
    }
}
