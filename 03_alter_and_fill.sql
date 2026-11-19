USE lotus_university;

-- ===== 1. students: current year and semester =====
ALTER TABLE students
  ADD COLUMN current_year     TINYINT NOT NULL DEFAULT 1 AFTER batch,
  ADD COLUMN current_semester TINYINT NOT NULL DEFAULT 1 AFTER current_year;

-- Fall 2026 ধরে: ভর্তির সাল থেকে semester বের করা (সর্বোচ্চ 8)
UPDATE students
   SET current_semester = LEAST((2026 - CAST(batch AS UNSIGNED)) * 2 + 1, 8);
UPDATE students
   SET current_year = CEIL(current_semester / 2);

-- ===== 2. complaints: subject and category =====
ALTER TABLE complaints
  ADD COLUMN subject  VARCHAR(200) NOT NULL DEFAULT '' AFTER user_id,
  ADD COLUMN category ENUM('Academic','Facilities','Administrative','Finance','Other')
                      NOT NULL DEFAULT 'Other' AFTER subject;

UPDATE complaints
   SET subject = LEFT(message, 200),
       category = CASE
         WHEN message LIKE '%Wi-Fi%' OR message LIKE '%projector%' THEN 'Facilities'
         WHEN message LIKE '%profile%' THEN 'Administrative'
         ELSE 'Academic'
       END;

-- ===== 3. notices: category and audience =====
ALTER TABLE notices
  ADD COLUMN category ENUM('Academic','General','Event','Finance')
                      NOT NULL DEFAULT 'General' AFTER body,
  ADD COLUMN audience ENUM('all','students','faculty','students_faculty')
                      NOT NULL DEFAULT 'all' AFTER category;

UPDATE notices
   SET category = CASE
         WHEN title LIKE '%Fee%' OR title LIKE '%Scholarship%' THEN 'Finance'
         WHEN title LIKE '%Sports%' OR title LIKE '%Seminar%' OR title LIKE '%Convocation%' THEN 'Event'
         WHEN title LIKE '%Exam%' OR title LIKE '%Result%' OR title LIKE '%Registration%'
              OR title LIKE '%Course%' OR title LIKE '%Class%' THEN 'Academic'
         ELSE 'General'
       END,
       audience = CASE
         WHEN title LIKE '%Seminar%' THEN 'students_faculty'
         WHEN title LIKE '%Fee%' OR title LIKE '%Scholarship%' OR title LIKE '%Registration%'
              OR title LIKE '%Result%' OR title LIKE '%Sports%' THEN 'students'
         ELSE 'all'
       END;

-- ===== 4. results: assessment (Midterm / Final) =====
-- নতুন unique key আগে যোগ করে পুরোনোটা একই কমান্ডে বাদ দেওয়া হচ্ছে
ALTER TABLE results
  ADD COLUMN assessment VARCHAR(20) NOT NULL DEFAULT 'Final' AFTER semester,
  ADD UNIQUE KEY uq_result (student_id, course_id, semester, assessment),
  DROP INDEX student_id;

-- আগের সব result এখন 'Final'। প্রতিটার জন্য একটা 'Midterm' result যোগ করা হচ্ছে
INSERT INTO results (student_id, course_id, semester, assessment, marks, grade)
SELECT student_id, course_id, semester, 'Midterm', m,
       CASE WHEN m >= 80 THEN 'A+' WHEN m >= 75 THEN 'A' WHEN m >= 70 THEN 'A-'
            WHEN m >= 65 THEN 'B+' WHEN m >= 60 THEN 'B' WHEN m >= 55 THEN 'B-'
            WHEN m >= 50 THEN 'C+' WHEN m >= 45 THEN 'C' WHEN m >= 40 THEN 'D'
            ELSE 'F' END
FROM (
  SELECT student_id, course_id, semester,
         GREATEST(20, LEAST(100, ROUND(marks + (RAND() * 20 - 10), 2))) AS m
  FROM results
  WHERE assessment = 'Final'
) t;

-- ===== যাচাই =====
SELECT batch, current_year, current_semester, COUNT(*) AS total
  FROM students GROUP BY batch, current_year, current_semester ORDER BY batch;
SELECT assessment, COUNT(*) FROM results GROUP BY assessment;
SELECT category, COUNT(*) FROM complaints GROUP BY category;
SELECT category, audience, title FROM notices;
