FROM nginx:1.25-alpine

# Create cache directory
RUN mkdir -p /var/cache/nginx/s3_cache && \
    chown -R nginx:nginx /var/cache/nginx

# Copy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
