# Creating and enrolling users

There are two files in this folder along with this README:

- create2users.csv
- enroll2students.csv

These are Blackboard Learn format files for bulk loading users and enrollments.

1. Create a course in Learn and give it the COURSE_ID of `aws-workshop`. You may give it a different name but you'll have to update the enroll2students.csv file
2. As Learn Administrator in the Admin panel navigate to `Users` and select `Create Users` under the `Batch Actions` menu
3. Browse to the `create2users.csv file`, select it, and click `Submit`. You should get a success message
4. Back in the main Admin panel, select `Courses` and click `Enroll Users`
5. Browse to the enroll2students.csv file, select it, and click `Submit`
6. You should get both students from the previous file enrolled in the course you just created.

See these help pages for more information on the format of the batch files:

https://help.blackboard.com/Learn/Administrator/Hosting/User_Management/Batch_File_Guidelines_for_User_Accounts
https://help.blackboard.com/Learn/Administrator/Hosting/Course_Management/Managing_Enrollments/Batch_File_Guidelines_for_Enrollments
