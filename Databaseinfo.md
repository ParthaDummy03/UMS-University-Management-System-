ডেটার পরিমাণ: 
৩০ admin, 
২০০ faculty, 
২,৫০০ student। 
এর সাথে ৫টা department, 
৪০টা course (প্রতিdepartment-এ ৮টা), 
৮০টা class schedule, 
১২,৫০০ enrollment, 
৩৭,৫০০ attendance, 
১২,৫০০ result, 
৬০টা complaint, 
১২টা notice।




ID-র নিয়ম:
Student: ৯ ডিজিট। 
প্রথম ২ ডিজিট ভর্তির সাল (২২ থেকে ২৫), 
মাঝের ৫ ডিজিট random, 
শেষ ২ ডিজিট department code। 
যেমন 223933212, কোনো ID ডুপ্লিকেট নেই।
Department code: 
CSE 12,
EEE 10, 
Economics 14, 
English 16, 
Social Economics 18।
Faculty: F + department code + ৩ ডিজিট, 
যেমন F12001।
Admin: A001 থেকে A030।




Login-এর জন্য:
সব user-এর password একই: [development-only password - rotate before deployment]।
এটা Django-র নিজস্ব hash format-এ রাখা আছে, 
তাই backend থেকে সরাসরি login হবে।
Admin-এর email admin01@lotus.edu থেকে admin30@lotus.edu। admin01 superuser।
Student-এর email <student_id>@student.lotus.edu, যেমন 223933212@student.lotus.edu।
Faculty-র email firstname.lastname@lotus.edu