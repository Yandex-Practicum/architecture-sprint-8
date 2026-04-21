FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS base
WORKDIR /app
EXPOSE 8080

FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build
WORKDIR /src
COPY ["./bionicpro-auth/bionicpro-auth.csproj", "."]
RUN dotnet restore "./bionicpro-auth.csproj"
COPY ./bionicpro-auth .
RUN dotnet build "bionicpro-auth.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "bionicpro-auth.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "bionicpro-auth.dll"]