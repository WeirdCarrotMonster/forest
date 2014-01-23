function Leaves($scope, $http, $timeout) {
    $scope.leaves = [];
    $scope.leaf_settings = "";
    $scope.leaf_address = "";
    $scope.settings_element = null;
    $scope.logs_element = null;
    $scope.logs_loaded = false;
    $scope.logs = [];
    $scope.branches = [];
    $scope.types = [
        {
            name: "espresso",
            settings: [
                {
                    verbose: "Стиль",
                    name: "style",
                    type: "select",
                    choices: [
                        {
                            name: "Эспрессо",
                            value: "espresso"
                        },
                        {
                            name: "Кофелайк",
                            value: "like-coffee"
                        }
                    ]
                }
            ]
        },
        {
            name: "clients",
            settings: [
                {
                    verbose: "Ограничение филиалов",
                    name: "unit-limit",
                    type: "input-int",
                    min_value: 1,
                    max_value: 100
                }
            ]
        }
    ];
    $scope.add_leaf_show = false;
    $scope.new_leaf_type = null;
    $scope.new_leaf_name = "";
    $scope.new_leaf_address = "";

    $scope.addLeaf = function(){
        var settings = {};
        $("#new_leaf_settings").children().each(function(){
            settings[$(this).attr("data-key")] = $(this).val();
        });

        console.log({
            name: $scope.new_leaf_name,
            address: $scope.new_leaf_address,
            type: $scope.new_leaf_type.name,
            settings: settings
        })
    };

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

    $scope.closeLogs = function() {
        $scope.logs_element = null;
        $scope.logs_loaded = false;
    };

    $scope.openSettings = function(leaf) {
        $scope.settings_element = leaf;
        $scope.leaf_settings = JSON.stringify(leaf.settings, undefined, 2);
        $scope.leaf_address = leaf.address;
    };

    $scope.openLogs = function(leaf) {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "get_leaf_logs",
                name: leaf.name
            }
        }).
        success(function(data, status, headers, config) {
            if (data["result"] == "success"){
                $scope.logs = data["logs"];
                $scope.logs_loaded = true;
            }
        }).
        error(function(data, status, headers, config) {
        });
        $scope.logs_element = leaf;
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
        });
    };

    $scope.getBranches = function() {
        $http({
            method: 'POST',
            url: '/',
            data: {
                function: "list_branches"
            }
        }).
        success(function(data, status, headers, config) {
            $scope.branches = data["branches"];
        }).
        error(function(data, status, headers, config) {
        });
    };
    $scope.getBranches();
    $scope.getLeavesData();
}
