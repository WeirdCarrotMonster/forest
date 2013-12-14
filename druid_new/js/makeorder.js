menuUrl = 'http://127.0.0.1:8000/manage/api/api/1?function=getServices'

function SellService($scope) {
    $scope.service.qtyClass = "invisible-qty";
    $scope.incService = function () {
        $scope.service.qty++;
        $scope.$parent.$parent.wholeQTY++;
    }
    $scope.setVisible = function() {
        if ($scope.service.qty == 1) {
            $scope.service.qtyClass = "visible-qty";
        }
    }
    $scope.clearPosition = function () {
        $scope.$parent.$parent.wholeQTY -= $scope.service.qty + 1;
        $scope.service.qty = -1;
        $scope.service.qtyClass = "invisible-qty";
    }
}

function Services($scope, $http) {
    $scope.services = []
    $scope.orderList = [];
    $scope.orderSum = 0;
    $scope.wholeQTY = 0;
    $scope.orderListClass = "invisible-orderlist";

    $scope.loadData = function () {
        $http({method: 'JSONP', url: menuUrl}).
          success(function(data, status) {
            console.log('1',data,status);
            $scope.services = data;
          }).
          error(function(data, status) {
            console.log('2',data,status);
        });
    };
    //initial load
    $scope.loadData();
    $scope.updateOrderList = function (){
        var allPositions = $scope.services;
        $scope.orderList = []
        $scope.orderSum = 0;
        angular.forEach(allPositions, function(service){
            if (service.qty > 0) {
                   $scope.orderList.push(service);
                $scope.orderSum += service.price * service.qty;
            }
        });
    }

    $scope.ClearAllPositions = function() {
        var allPositions = $scope.services;
        $scope.wholeQTY = 0;
        angular.forEach(allPositions, function(service){
            if (service.qty > 0) {
                service.qty = 0;
                service.qtyClass = "invisible-qty";
            }
        });
    }
    $scope.showOrderList = function() {
        if ($scope.wholeQTY == 0) {
            $scope.orderListClass = "invisible-orderlist";
        } else {
            $scope.orderListClass = "visible-orderlist";
        }
    }
}


function OrderItem($scope){
}