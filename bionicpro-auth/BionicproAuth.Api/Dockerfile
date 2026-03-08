FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS base
USER $APP_UID
WORKDIR /app
EXPOSE 8080
EXPOSE 8081

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src
COPY ["BionicproAuth.Api/BionicproAuth.Api.csproj", "BionicproAuth.Api/"]
RUN dotnet restore "BionicproAuth.Api/BionicproAuth.Api.csproj"
COPY . .
WORKDIR "/src/BionicproAuth.Api"
RUN dotnet build "BionicproAuth.Api.csproj" -c $BUILD_CONFIGURATION -o /app/build

FROM build AS publish
ARG BUILD_CONFIGURATION=Release
RUN dotnet publish "BionicproAuth.Api.csproj" -c $BUILD_CONFIGURATION -o /app/publish /p:UseAppHost=false

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "BionicproAuth.Api.dll"]
