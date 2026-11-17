# Single sign-on of the subtitle application: Keycloak with the "subtitle" realm built in
# (imported at the first start by --import-realm, see docker-compose.yml).
FROM quay.io/keycloak/keycloak:26.0.7

COPY realm-subtitle.json /opt/keycloak/data/import/realm-subtitle.json

LABEL org.opencontainers.image.title="subtitle-keycloak" \
      org.opencontainers.image.description="Keycloak (OpenID Connect) with the realm of the subtitle application" \
      com.ynov.subtitle.component="sso"
