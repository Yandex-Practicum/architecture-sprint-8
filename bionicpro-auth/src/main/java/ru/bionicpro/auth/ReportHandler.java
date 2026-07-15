package ru.bionicpro.auth;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatusCode;
import org.springframework.security.oauth2.client.ReactiveOAuth2AuthorizedClientManager;
import org.springframework.security.oauth2.client.web.reactive.function.client.ServerOAuth2AuthorizedClientExchangeFilterFunction;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

@Component
public final class ReportHandler {

    private final WebClient apiWebClient;

    public ReportHandler(
            WebClient.Builder webClientBuilder,
            ReactiveOAuth2AuthorizedClientManager authorizedClientManager,
            @Value("${app.api.base-url}") String apiBaseUrl
    ) {
        ServerOAuth2AuthorizedClientExchangeFilterFunction filter = new ServerOAuth2AuthorizedClientExchangeFilterFunction(authorizedClientManager);
        filter.setDefaultOAuth2AuthorizedClient(true);

        this.apiWebClient = webClientBuilder
                .filter(filter)
                .baseUrl(apiBaseUrl)
                .build();
    }

    public Mono<ServerResponse> listReports(ServerRequest request) {
        return apiWebClient.get()
                .uri("/reports", uriBuilder -> uriBuilder
                        .queryParams(request.queryParams())
                        .build())
                .retrieve()
                .onStatus(HttpStatusCode::isError, this::handleError)
                .bodyToMono(String.class)
                .flatMap(this::handleResponse)
                .onErrorResume(ClientException.class, this::handleClientException);
    }

    private Mono<ClientException> handleError(ClientResponse clientResponse) {
        return clientResponse
                .bodyToMono(String.class)
                .defaultIfEmpty("")
                .flatMap(body -> Mono.error(new ClientException(clientResponse.statusCode(), body)));
    }

    private Mono<ServerResponse> handleResponse(String response) {
        return ServerResponse.ok()
                .bodyValue(response);
    }

    private Mono<ServerResponse> handleClientException(ClientException clientException) {
        return ServerResponse.status(clientException.getHttpStatusCode())
                .bodyValue(clientException.getBody());
    }

    private static final class ClientException extends RuntimeException {

        private final HttpStatusCode httpStatusCode;

        private final String body;

        public ClientException(HttpStatusCode httpStatusCode, String body) {
            this.httpStatusCode = httpStatusCode;
            this.body = body;
        }

        public HttpStatusCode getHttpStatusCode() {
            return httpStatusCode;
        }

        public String getBody() {
            return body;
        }

    }

}
