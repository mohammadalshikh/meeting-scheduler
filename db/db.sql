DROP DATABASE IF EXISTS meeting_scheduler;
CREATE DATABASE meeting_scheduler;

USE meeting_scheduler;

-- =========================================================
-- 1. USERS
-- =========================================================

CREATE TABLE users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') NOT NULL DEFAULT 'user',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


-- =========================================================
-- 2. ROOMS
-- =========================================================

CREATE TABLE rooms (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    capacity INT UNSIGNED NOT NULL,
    location VARCHAR(255),
    description VARCHAR(500),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_room_capacity CHECK (capacity > 0)
) ENGINE=InnoDB;


-- =========================================================
-- 3. RESERVATIONS
-- =========================================================

CREATE TABLE reservations (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    user_id INT UNSIGNED NOT NULL,
    room_id INT UNSIGNED NOT NULL,

    title VARCHAR(150) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,

    status ENUM('confirmed', 'cancelled') NOT NULL DEFAULT 'confirmed',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_reservation_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_reservation_room
        FOREIGN KEY (room_id)
        REFERENCES rooms(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT chk_reservation_time
        CHECK (end_time > start_time),

    INDEX idx_reservation_room_time (room_id, start_time, end_time),
    INDEX idx_reservation_user (user_id)
) ENGINE=InnoDB;


-- =========================================================
-- 4. AUDIT LOG
-- =========================================================

CREATE TABLE audit_log (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    user_id INT UNSIGNED NULL,

    table_name VARCHAR(100) NOT NULL,
    record_id INT UNSIGNED NULL,

    action ENUM('INSERT', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT')
        NOT NULL,

    old_data JSON NULL,
    new_data JSON NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_audit_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    INDEX idx_audit_table_record (table_name, record_id),
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_created_at (created_at)
) ENGINE=InnoDB;


-- =========================================================
-- 5. SAMPLE DATA
-- =========================================================

INSERT INTO rooms (name, capacity, location, description)
VALUES
    ('Room A', 4, '1st Floor', 'Small meeting room'),
    ('Room B', 8, '1st Floor', 'Medium meeting room'),
    ('Room C', 16, '2nd Floor', 'Large conference room'),
    ('Room D', 12, '2nd Floor', 'Presentation room');


INSERT INTO users (username, email, password_hash, role)
VALUES
    (
        'admin',
        'pladmin@gmail.com',
        'scrypt:32768:8:1$z67TLABU8bj33zvs$d580a42ba7eb1f94ae983affad92439be7f9bae5d63c06be33e6027f5e470ad41b885c2cc9da4e8d11558474a298984db71b398e8f5a82d752d15462c67c775a',
        'admin'
    ),
    (
        'mo',
        'pluser@gmail.com',
        'scrypt:32768:8:1$ol6R7VGPTXNtmd2E$92882b123ba77b7d924beac90f4d0d6fd5e1b0b1fff38b7c192d2e5816a33e9e64b17f4b3e1cb3d89718c13637087e3d3c14ca314f84279ecfe82b26156d385b',
        'user'
    );