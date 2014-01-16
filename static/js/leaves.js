function Leaves($scope, $http, $timeout) {
    $scope.leaves = [];

    $scope.shutdownLeaf = function(leaf) {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "disable_leaf",
                name: leaf.name
            }
        }).
        success(function(data, status, headers, config) {
            $scope.getLeavesData();
        }).
        error(function(data, status, headers, config) {
        });
    };

    $scope.getLeavesData = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "check_leaves"
            }
        }).
        success(function(data, status, headers, config) {
            $scope.leaves = [];
            var a = $.map(data["leaves"], function(value, index) {
               value["name"] = index;
               return [value];
           });
           console.log(a);
            while (a.length > 0){
                $scope.leaves.push(a.splice(0, 2));
           }
        }).
        error(function(data, status, headers, config) {
          // called asynchronously if an error occurs
          // or server returns response with an error status.
        });
    };
    $scope.getLeavesData();
}
