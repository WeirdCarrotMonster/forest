function Leaves($scope, $http, $timeout) {
    $scope.leaves = [];
    $scope.leaf_settings = "";
    $scope.leaf_address = "";
    $scope.settings_element = null;
    $scope.branches = [
        {name: "strong", type: "espresso"},
        {name: "main", type: "espresso"},
        {name: "second", type: "espresso"},
        {name: "main_clients", type: "clients"}
    ];

    $scope.migrateLeaf = function(leaf) {
        leaf.selectEnabled = false;
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "migrate_leaf",
                name: leaf.name,
                destination: leaf.new_branch
            }
        }).
        success(function(data, status, headers, config) {
            $scope.getLeavesData();
        }).
        error(function(data, status, headers, config) {
        });
    };

    $scope.acceptableBranches = function(leaf) {
        var result = [];
        angular.forEach($scope.branches, function(value, key){
            if(value.type == leaf.type){
                result.push(value.name);
            }
        }, result);
        return result;
    };

    $scope.closeSettings = function() {
        $scope.settings_element = null; 
    };

    $scope.openSettings = function(leaf) {
        $scope.settings_element = leaf;
        $scope.leaf_settings = JSON.stringify(leaf.settings, undefined, 2);
        $scope.leaf_address = leaf.address;
    };

    $scope.saveSettings = function() {
        var changed = false;
        if ($scope.settings_element.settings != JSON.parse($scope.leaf_settings)){
            changed = true;
            $http({
                method: 'POST',
                url: '/',
                data: {
                    function: "change_settings",
                    name: $scope.settings_element.name,
                    settings: $scope.leaf_settings
                }
            }).
            success(function(data, status, headers, config) {
                $scope.closeSettings();
                $scope.getLeavesData();
            }).
            error(function(data, status, headers, config) {
            });
        }
        if ($scope.settings_element.address != $scope.leaf_address){
            changed = true;
            $http({
                method: 'POST',
                url: '/',
                data: {
                    function: "rehost_leaf",
                    name: $scope.settings_element.name,
                    address: $scope.leaf_address
                }
            }).
            success(function(data, status, headers, config) {
                $scope.closeSettings();
                $scope.getLeavesData();
            }).
            error(function(data, status, headers, config) {
            });
        }
        if (!changed)$scope.closeSettings();
    };

    $scope.enableLeaf = function(leaf) {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "enable_leaf",
                name: leaf.name
            }
        }).
        success(function(data, status, headers, config) {
            $scope.getLeavesData();
        }).
        error(function(data, status, headers, config) {
        });
    };



    $scope.disableLeaf = function(leaf) {
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
