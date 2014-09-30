forest.factory("Leaves", function($resource) {
  return $resource("/api/leaves/:id/:query", null, {
    'update': {method: 'PATCH', params: {id: "@_id"}}
  });
});

forest.factory("Species", function($resource) {
  return $resource("/api/species/:id/:query");
});