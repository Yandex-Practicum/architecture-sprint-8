package com.bionicpro.auth.profile;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserYandexProfileRepository extends JpaRepository<UserYandexProfile, Long> {

    Optional<UserYandexProfile> findByKeycloakSubject(String keycloakSubject);
}
