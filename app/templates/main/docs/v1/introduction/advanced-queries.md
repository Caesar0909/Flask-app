
### Parameters and Advanced API Queries

Advanced querying options can be used to reduce the number of data points or
other resources returned at any point. Most API methods in place with the Tata
AQ API are able to use these techniques. The three primary tools are `filter`,
`limit`, and `sort`.

#### Filtering Queries

To filter a query, use the `filter` keyword argument with the format
`filter=parameter,filter-spec,value`. Multiple filter arguments can be separated
by a semicolon (e.g. `filter=city,eq,Delhi;parameter,eq,pm25`). The filter-spec's
that can be used are:

  * `eq`: equals
  * `ne`: not equals
  * `lt`: less than
  * `gt`: greater than
  * `ge`: greater than or equal to
  * `le`: less than or equal to
  * `in`: in
  * `like`: like

#### Limiting Queries

To limit the number of responses in a query for API endpoints that are paginated,
 you can use the `per_page` and `page` keywords. For example, to grab only 5
 of an object you would use `per_page=5`.

#### Sorting Queries

To sort a query, simply use the `sort` keyword argument with the format
`sort=parameter,[asc,desc]`. For example, to sort ascending based on the
column `last_updated`, you would send the keyword argument `sort=last_updated,asc`.
