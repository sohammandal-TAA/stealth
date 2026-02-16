package ai.theaware.stealth.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import ai.theaware.stealth.entity.Users;

public interface UserRepository extends JpaRepository<Users, String> {
}