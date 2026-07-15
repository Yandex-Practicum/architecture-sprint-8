package ru.bionicpro.auth;

import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.server.ServerRequest;
import org.springframework.web.reactive.function.server.ServerResponse;
import reactor.core.publisher.Mono;

@Component
public final class StatusHandler {

    public Mono<ServerResponse> getStatus(ServerRequest request) {
        return request.principal()
                .map(principal -> new StatusResponse(true))
                .defaultIfEmpty(new StatusResponse(false))
                .flatMap(response -> ServerResponse.ok()
                        .bodyValue(response));
    }

}
