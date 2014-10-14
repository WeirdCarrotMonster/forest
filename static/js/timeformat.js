angular.module('Filters', []).filter('timeformat', function() {
    return function(input) {
        moment.lang("ru");
        return moment(input).format('LLLL');
    };
});