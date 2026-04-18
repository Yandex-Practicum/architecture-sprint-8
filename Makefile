COMPOSE := docker-compose

# Корень: Keycloak, reports-api, frontend
ROOT_COMPOSE := docker-compose.yaml

# OLAP: Postgres (sample + Airflow), ClickHouse, Airflow — пути в compose относительно dags/
DAGS_DIR := dags

.PHONY: help \
	up up-build down build logs ps restart \
	up-dags up-dags-build down-dags build-dags logs-dags ps-dags restart-dags \
	up-all down-all build-all

.DEFAULT_GOAL := help

help: ## Справка по целям
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Приложение (Keycloak :8090, API :8000, фронт :3000) ---
up: ## Приложение: up -d
	$(COMPOSE) -f $(ROOT_COMPOSE) up -d

up-build: ## Приложение: up -d --build (фронт с REACT_APP_* из compose)
	$(COMPOSE) -f $(ROOT_COMPOSE) up -d --build

down: ## Приложение: down
	$(COMPOSE) -f $(ROOT_COMPOSE) down

build: ## Приложение: build образов
	$(COMPOSE) -f $(ROOT_COMPOSE) build

logs: ## Приложение: логи (follow)
	$(COMPOSE) -f $(ROOT_COMPOSE) logs -f

ps: ## Приложение: статус контейнеров
	$(COMPOSE) -f $(ROOT_COMPOSE) ps

restart: ## Приложение: restart
	$(COMPOSE) -f $(ROOT_COMPOSE) restart

# --- OLAP (Airflow :8080, ClickHouse :8123) — команды из каталога dags/ ---
up-dags: ## OLAP: up -d
	cd $(DAGS_DIR) && $(COMPOSE) up -d

up-dags-build: ## OLAP: up -d --build
	cd $(DAGS_DIR) && $(COMPOSE) up -d --build

down-dags: ## OLAP: down
	cd $(DAGS_DIR) && $(COMPOSE) down

build-dags: ## OLAP: build
	cd $(DAGS_DIR) && $(COMPOSE) build

logs-dags: ## OLAP: логи (follow)
	cd $(DAGS_DIR) && $(COMPOSE) logs -f

ps-dags: ## OLAP: статус
	cd $(DAGS_DIR) && $(COMPOSE) ps

restart-dags: ## OLAP: restart
	cd $(DAGS_DIR) && $(COMPOSE) restart

# --- Оба стека (сначала OLAP — нужен ClickHouse для reports-api) ---
up-all: ## Сначала OLAP, затем приложение
	$(MAKE) up-dags
	$(MAKE) up

up-all-build: ## up-all с --build для обоих compose
	$(MAKE) up-dags-build
	$(MAKE) up-build

down-all: ## Остановить приложение и OLAP
	$(COMPOSE) -f $(ROOT_COMPOSE) down
	cd $(DAGS_DIR) && $(COMPOSE) down

build-all: ## build в dags/, затем в корне
	cd $(DAGS_DIR) && $(COMPOSE) build
	$(COMPOSE) -f $(ROOT_COMPOSE) build
