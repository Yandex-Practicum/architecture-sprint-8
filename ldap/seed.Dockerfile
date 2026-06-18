FROM alpine:3.19

RUN apk add --no-cache openldap-clients bash

COPY bootstrap/01-bionicpro.ldif /seed.ldif
COPY seed.sh /seed.sh
RUN chmod +x /seed.sh

ENTRYPOINT ["/seed.sh"]