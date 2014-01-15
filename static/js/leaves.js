function Leaves($scope, $http, $timeout) {
    $scope.leaves = [];

    $scope.getNiceLookingPercent = function(part, all){
        if (all == 0){
            all = 100;
        }
        return ((part/all)*100).toFixed(0);
    };

    $scope.getLoadClass = function(part, all){
        if (all == 0){
            all = 100;
        }
        if ((part/all)*100 > 75){
            return "red";
        }
        else{
            return "green"
        }
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
            $scope.leaves = data["leaves"];
            console.log(data);
        }).
        error(function(data, status, headers, config) {
          // called asynchronously if an error occurs
          // or server returns response with an error status.
        });
    };
    $scope.getLeavesData();
}