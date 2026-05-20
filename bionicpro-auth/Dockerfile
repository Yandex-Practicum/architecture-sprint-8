FROM php:8.2-cli-alpine

# Install system dependencies and PHP extensions
RUN apk add --no-cache \
    unzip \
    libzip-dev \
    && docker-php-ext-install zip

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

WORKDIR /var/www

# Copy composer files first to leverage Docker cache
COPY composer.json ./

# Install dependencies
RUN composer install --no-dev --no-interaction --no-scripts --prefer-dist

# Copy the rest of the application
COPY . .

# Generate classmap
RUN composer dump-autoload --optimize

EXPOSE 8081

# Start the PHP built-in web server for Slim
CMD ["php", "-S", "0.0.0.0:8081", "-t", "public"]
