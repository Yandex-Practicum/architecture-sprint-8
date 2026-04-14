#!/bin/sh

mkcert -install

domains="
  front.bio-pro.local
  api.bio-pro.local
  key.bio-pro.local
"

certPath="./certs"

for domain in $domains; do
  # Пропускаем пустые строки
  if [ -z "$domain" ]; then
    continue
  fi
  
  mkcert -key-file "$certPath/$domain.key" -cert-file "$certPath/$domain.crt" "$domain"
done