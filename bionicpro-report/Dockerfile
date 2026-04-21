FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS base
WORKDIR /app
EXPOSE 8080

FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build
WORKDIR /src
COPY ["./bionicpro-report.csproj", "."]
RUN dotnet restore "./bionicpro-report.csproj"
COPY . .
RUN dotnet build "bionicpro-report.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "bionicpro-report.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "bionicpro-report.dll"]