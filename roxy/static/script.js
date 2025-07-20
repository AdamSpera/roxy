$(document).ready(function() {
    // Initialize search history array
    var searchHistory = JSON.parse(Cookies.get('searchHistory') || '[]');

    $("#searchButton").click(function() {
        currentUrl = window.location.href;
        baseDomain = currentUrl.split('//')[1].split('/')[0].trim()
        protocol = $('#protocols').find(":selected").val().trim();
        destinationIP = $('#searchBar').val().trim();
        window.open(`https://${baseDomain}/?protocol=${protocol}&ip=${destinationIP}`, '_blank');

        // Add search to history
        searchHistory.push({protocol: protocol, ip: destinationIP, date: new Date().toLocaleString()});

        // Update search history table
        updateSearchHistoryTable();

        // Save search history to cookie
        Cookies.set('searchHistory', JSON.stringify(searchHistory));
    });

    $("#searchBar").keypress(function(e) {
        if (e.which == 13) { // Enter key pressed
            $("#searchButton").click(); // Trigger search button click event
        }
    });

    $("#filterBar").keyup(function() {
        var searchQuery = $(this).val().trim();
        console.log(searchQuery);
        updateSearchHistoryTable(searchQuery);
    });

    // Clear search bar and history on clear button click
    $("#clearBtn").click(function() {
        $('#searchBar').val('');
        searchHistory = [];
        Cookies.set('searchHistory', JSON.stringify(searchHistory));
        updateSearchHistoryTable();
    });

    function updateSearchHistoryTable(query = '') {
        // Clear table body
        $(".table-responsive tbody").empty();

        // Add each search to the table
        searchHistory.forEach(function(search, index) {
            if (search.ip.includes(query) || search.protocol.includes(query)) {
                $(".table-responsive tbody").append(`
                    <tr>
                        <td>${index + 1}</td>
                        <td>${search.ip}</td>
                        <td>${search.protocol}</td>
                        <td>${search.date}</td>
                        <td>
                            <button class="m-btn tertiary quick-search" data-index="${index}">Search</button>
                            <button class="m-btn tertiary remove-item" data-index="${index}">Remove</button>
                        </td>
                    </tr>
                `);
            }
        });

        // Add click event to quick search buttons
        $(".quick-search").click(function() {
            var index = $(this).data("index");
            var search = searchHistory[index];
            $('#protocols').val(search.protocol);
            $('#searchBar').val(search.ip);
            $("#searchButton").click();
        });

        // Add click event to remove buttons
        $(".remove-item").click(function() {
            var index = $(this).data("index");
            searchHistory.splice(index, 1);
            Cookies.set('searchHistory', JSON.stringify(searchHistory));
            updateSearchHistoryTable();
        });
    }

    // Update search history table on page load
    updateSearchHistoryTable();
});