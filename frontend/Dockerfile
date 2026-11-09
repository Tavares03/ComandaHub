# Dependencias (cache entre os estagios)
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Desenvolvimento: ng serve na porta 4200 (API em http://localhost:8000)
FROM deps AS dev
COPY . .
EXPOSE 4200
CMD ["npm", "start"]

# Build de producao
FROM deps AS build
COPY . .
RUN npm run build

# Producao: nginx serve o painel e repassa /api para o backend
FROM nginx:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/comandahub-frontend/browser /usr/share/nginx/html
EXPOSE 80
