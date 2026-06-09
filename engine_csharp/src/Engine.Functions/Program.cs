using Engine.Functions;
using Microsoft.AspNetCore.Http.Json;
using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);

builder.WebHost.UseUrls(ListenUrl());
builder.Services.Configure<JsonOptions>(options =>
{
    options.SerializerOptions.PropertyNameCaseInsensitive = true;
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
});
builder.Services.AddSingleton<ChessMoveHandler>();

var app = builder.Build();

app.UseCorsHeaders();

app.MapGet("/", () => Results.Text("Why are you here? 0.0", "text/plain"));

app.MapGet("/healthz", () => Results.Ok(new { status = "ok" }));

app.MapGet("/api/chess/metadata", async () =>
{
    var path = FindChangelogPath();
    if (!File.Exists(path))
    {
        return Results.Json(
            new
            {
                schema_version = 2,
                error = "CHANGELOG.json not found",
                evaluation_opponents = new Dictionary<string, object>(),
                versions = Array.Empty<object>(),
            },
            statusCode: StatusCodes.Status500InternalServerError);
    }

    var json = await File.ReadAllTextAsync(path);
    return Results.Text(json, "application/json");
});

app.MapPost("/api/chess/{version}", async (string version, HttpContext context, ChessMoveHandler handler) =>
{
    var request = await ReadRequest(context);
    if (request.Error is not null)
    {
        return Results.Json(request.Error.Body, statusCode: request.Error.StatusCode);
    }

    var response = handler.Generate(version, request.Payload);
    return Results.Json(response.Body, statusCode: response.StatusCode);
});

app.MapMethods("/api/chess/{version}", ["OPTIONS"], () => Results.NoContent());

app.Run();

static string ListenUrl()
{
    var port = Environment.GetEnvironmentVariable("PORT");
    if (string.IsNullOrWhiteSpace(port))
    {
        port = "8080";
    }

    return $"http://0.0.0.0:{port}";
}

static string FindChangelogPath()
{
    const string fileName = "CHANGELOG.json";
    var outputPath = Path.Combine(AppContext.BaseDirectory, fileName);
    if (File.Exists(outputPath))
    {
        return outputPath;
    }

    var current = new DirectoryInfo(AppContext.BaseDirectory);
    while (current is not null)
    {
        var candidate = Path.GetFullPath(Path.Combine(current.FullName, "..", "..", "..", ".."));
        var changelogPath = Path.Combine(candidate, fileName);
        if (File.Exists(changelogPath)
            && File.Exists(Path.Combine(candidate, "README.md"))
            && Directory.Exists(Path.Combine(candidate, "engine_csharp")))
        {
            return changelogPath;
        }

        current = current.Parent;
    }

    return Path.Combine(Directory.GetCurrentDirectory(), fileName);
}

static async Task<ParsedChessRequest> ReadRequest(HttpContext context)
{
    using var reader = new StreamReader(context.Request.Body);
    var body = await reader.ReadToEndAsync();
    if (string.IsNullOrWhiteSpace(body))
    {
        return new ParsedChessRequest(new ChessRequest());
    }

    try
    {
        var payload = JsonSerializer.Deserialize<ChessRequest>(
            body,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            });
        return new ParsedChessRequest(payload ?? new ChessRequest());
    }
    catch (JsonException exc)
    {
        var version = context.Request.RouteValues["version"]?.ToString() ?? string.Empty;
        return new ParsedChessRequest(
            new ChessRequest(),
            ChessMoveHandler.InvalidJsonResponse(version, exc.Message));
    }
}

internal sealed record ParsedChessRequest(ChessRequest Payload, ChessResponse? Error = null);
