FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY engine_csharp/ChessEngine.sln engine_csharp/
COPY engine_csharp/src/Engine.Core/Engine.Core.csproj engine_csharp/src/Engine.Core/
COPY engine_csharp/src/Engine.Functions/Engine.Functions.csproj engine_csharp/src/Engine.Functions/
COPY engine_csharp/src/LocalTesting/LocalTesting.csproj engine_csharp/src/LocalTesting/
RUN dotnet restore engine_csharp/src/Engine.Functions/Engine.Functions.csproj

COPY . .
RUN dotnet publish engine_csharp/src/Engine.Functions/Engine.Functions.csproj \
    --configuration Release \
    --no-restore \
    --output /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_ENVIRONMENT=Production
EXPOSE 8080
ENTRYPOINT ["dotnet", "Engine.Functions.dll"]
