function Login($scope, $http, $location) {
    $scope.username = "";
    $scope.password = "";

    $scope.loginUser = function() {
        var data = {
            "function": "login_user",
            "username": $scope.username,
            "password": $scope.password
        };
        $http({
            method: 'POST',
            url: "/",
            data: JSON.stringify(data)
        }).
        success(function(data, status) {
            if (data["result"] == "success"){
                window.location.href = "/dashboard";
            }
            else{
                $(".login").removeClass("fadeInDown").removeClass("shake")
                $(".login").addClass("shake").removeClass("shake");
            }
        }).
        error(function(data, status) {
        });
    };
}