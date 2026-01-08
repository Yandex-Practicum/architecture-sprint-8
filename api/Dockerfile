FROM node:23-slim

WORKDIR /app

COPY package*.json package-lock.json ./

COPY . .

RUN npm install

EXPOSE 8000

ENTRYPOINT ["npm", "start"]
