# Housing Discrimination
### __Description__:
(Description Here)

### Workflow Diagram:
![alt text](https://github.com/uiuc-bdeep/Housing-Discrimination/blob/master/workflow_trulia_project.png)

### __File Hierarchy__:
```
Housing-Discrimination
+--README.md
+--workflow_trulia_project.png
+--.gitignore
+--scripts
|  +--listings_crawler
|  |  +--rhgeo_vm.py
|  +--listings_inquirer
|  |  +--trulia_rental_message_sender.py
|  |  +--trulia_rental_message_sender_data.txt
|  +--post_processing
|  |  +--adding_census_blocks_CA.R
|  |  +--mergeData.py
|  |  +--step_1_get_survey.R
|  +--pre_processing
|  |  +--trulia_rental_address_allocator.py
|  |  +--trulia_rental_address_allocator_data.txt
|  |  +--zip_url_finder.py
|  +--survey_gen
|  |  +--other survey stuff.csv
|  |  +--survey.py
|  |  +--test_template.xls
+--stores
|  +--atlanta_ga
|  |  +--atlanta_ga_final.csv
|  +--houston_tx
|  |  +--houston_tx_final.csv
|  +--los_angeles_ca
|  |  +--los_angeles_ca_final.csv
```
