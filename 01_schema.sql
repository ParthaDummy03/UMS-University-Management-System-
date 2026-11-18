DROP DATABASE IF EXISTS lotus_university;
CREATE DATABASE lotus_university
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lotus_university;

CREATE TABLE users (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  password      VARCHAR(128) NOT NULL,
  last_login    DATETIME NULL,
  is_superuser  TINYINT(1) NOT NULL DEFAULT 0,
  email         VARCHAR(254) NOT NULL UNIQUE,
  full_name     VARCHAR(150) NOT NULL,
  role          ENUM('admin','faculty','student') NOT NULL,
  is_staff      TINYINT(1) NOT NULL DEFAULT 0,
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  date_joined   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE departments (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  code             CHAR(2) NOT NULL UNIQUE,      -- 12=CSE, 10=EEE, 14=Economics, 16=English, 18=Social Economics
  name             VARCHAR(100) NOT NULL UNIQUE,
  head_faculty_id  BIGINT NULL
) ENGINE=InnoDB;

CREATE TABLE admins (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT NOT NULL UNIQUE,
  admin_code  VARCHAR(10) NOT NULL UNIQUE,       -- A001 ... A030
  designation VARCHAR(100) NULL,
  phone       VARCHAR(20) NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE faculty (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id       BIGINT NOT NULL UNIQUE,
  faculty_code  VARCHAR(10) NOT NULL UNIQUE,     -- F + dept code + 3 digits, e.g. F12001
  dept_id       BIGINT NOT NULL,
  designation   VARCHAR(100) NULL,
  phone         VARCHAR(20) NULL,
  joined_on     DATE NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (dept_id) REFERENCES departments(id)
) ENGINE=InnoDB;

ALTER TABLE departments
  ADD FOREIGN KEY (head_faculty_id) REFERENCES faculty(id) ON DELETE SET NULL;

CREATE TABLE students (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id        BIGINT NOT NULL UNIQUE,
  student_code   CHAR(9) NOT NULL UNIQUE,        -- YY + 5 random digits + dept code
  dept_id        BIGINT NOT NULL,
  batch          VARCHAR(20) NULL,
  status         ENUM('active','inactive') NOT NULL DEFAULT 'active',
  phone          VARCHAR(20) NULL,
  gender         ENUM('male','female') NULL,
  date_of_birth  DATE NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (dept_id) REFERENCES departments(id)
) ENGINE=InnoDB;

CREATE TABLE courses (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  code        VARCHAR(20) NOT NULL UNIQUE,
  name        VARCHAR(150) NOT NULL,
  credit      DECIMAL(3,1) NOT NULL,
  dept_id     BIGINT NOT NULL,
  faculty_id  BIGINT NULL,
  FOREIGN KEY (dept_id) REFERENCES departments(id),
  FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE enrollments (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  student_id  BIGINT NOT NULL,
  course_id   BIGINT NOT NULL,
  semester    VARCHAR(20) NOT NULL,
  UNIQUE (student_id, course_id, semester),
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE attendance (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  student_id  BIGINT NOT NULL,
  course_id   BIGINT NOT NULL,
  date        DATE NOT NULL,
  status      ENUM('present','absent','late') NOT NULL,
  UNIQUE (student_id, course_id, date),
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE schedules (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  course_id   BIGINT NOT NULL,
  day         ENUM('Sat','Sun','Mon','Tue','Wed','Thu','Fri') NOT NULL,
  start_time  TIME NOT NULL,
  end_time    TIME NOT NULL,
  room        VARCHAR(30) NULL,
  FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE results (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  student_id  BIGINT NOT NULL,
  course_id   BIGINT NOT NULL,
  semester    VARCHAR(20) NOT NULL,
  marks       DECIMAL(5,2) NULL,
  grade       VARCHAR(3) NULL,
  UNIQUE (student_id, course_id, semester),
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE complaints (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT NOT NULL,
  message     TEXT NOT NULL,
  status      ENUM('pending','in_progress','resolved') NOT NULL DEFAULT 'pending',
  response    TEXT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE notices (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(200) NOT NULL,
  body        TEXT NOT NULL,
  posted_by   BIGINT NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (posted_by) REFERENCES users(id)
) ENGINE=InnoDB;
