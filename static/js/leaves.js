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
            $scope.leaves = [];
            var a = $.map(data["leaves"], function(value, index) {
               value["name"] = index;
               return [value];
           });
           console.log(a);
            while (a.length > 0){
               console.log("processing shit");
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
