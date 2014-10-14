forest.controller("SpeciesIndex", function($scope, $rootScope, Species) {
  Species.query(function(data) {
    $scope.species = data;
  });
})

forest.controller("SpeciesIndexItem", function($scope, $routeSegment, Species) {
  $scope.init = function(data) {
    $scope.resource = data;
  };
  $scope.busy = false;
  $scope.update = function() {
    $scope.busy = true;
    $scope.resource.$update().then(function (a){
      $scope.busy = false;
    });
  };
});