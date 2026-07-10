FROM ghcr.io/cirruslabs/flutter:stable AS build
WORKDIR /app
COPY apps/mobile .
RUN flutter pub get && flutter build web

FROM nginx:1.27-alpine
COPY --from=build /app/build/web /usr/share/nginx/html
EXPOSE 80
