<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xsl:version="1.0">
<head>
    <link rel="stylesheet" href="/templates/table.css"/>
    <link rel="stylesheet" href="/templates/streams.css"/>
    <script type="text/javascript" src="/templates/streams_sort.js"/>
</head>
<body>
    <h1><xsl:value-of select="root/app_name"/> streams:</h1>
    <table>
        <thead>
            <tr>
                <th>Stream <span class="sort-arrow"/></th>
                <th>Group <span class="sort-arrow"/></th>
                <th>Consumer <span class="sort-arrow"/></th>
                <th>Last seen (sec ago) <span class="sort-arrow"/></th>
                <th>Message received (sec ago) <span class="sort-arrow"/></th>
                <th>Pending message <span class="sort-arrow"/></th>
            </tr>
        </thead>
        <tbody>
            <xsl:for-each select="root/groups/item">
                <xsl:variable name="stream_id" select="stream_id"/>
                <xsl:variable name="group_id" select="group_id"/>
                <xsl:for-each select="consumers/item">
                    <tr>
                        <td><xsl:value-of select="$stream_id"/></td>
                        <td><xsl:value-of select="$group_id"/></td>
                        <td><xsl:value-of select="name"/></td>
                        <td class="digits"><xsl:value-of select="seconds_since_last_seen"/></td>
                        <td class="digits"><xsl:value-of select="seconds_since_last_active"/></td>
                        <td>
                            <xsl:for-each select="pending/item">
                                <a href="{href}"><xsl:value-of select="message_id"/></a>
                                <br/>
                            </xsl:for-each>
                        </td>
                    </tr>
                </xsl:for-each>
            </xsl:for-each>
        </tbody>
    </table>
</body>
</html>
