<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:template match="/">
<html>
<head>
    <link rel="stylesheet" href="/templates/main.css"/>
    <script type="application/javascript" src="https://us.nxft.dev/static/debug.js"/>
    <script>
        window.onload = debug_update_display_style;  // See: https://bugzilla.mozilla.org/show_bug.cgi?id=325891
    </script>
</head>
<body>
    <h1>
        <a href="{root/phase/url}">
            <xsl:value-of select="root/phase/name"/>
        </a>
    </h1>
    <h2><a href="{root/batch_url}">FT Batch</a></h2>
    <fieldset class="page-action-block">
        <legend>Send results to TestRail</legend>
        <form action="/send_results" method="post">
            <div>
                <input type="hidden" name="phase_id" value="{root/request/phase_id}" />
                <details>
                    <summary>Data</summary>
                    <textarea name="requests"><xsl:value-of select="root/reports_json"/></textarea>
                </details>
            </div>
            <div>
                <input type="submit" value="Send" class="submit-btn" />
            </div>
        </form>
    </fieldset>
    <fieldset class="page-action-block">
        <legend>Legend</legend>
        <pre>Fully matched stage</pre>
        <pre class="mismatched">No linked stage for this test</pre>
    </fieldset>
    <xsl:for-each select="root/reports/item">
    <xsl:variable name="run_id" select="run_id"/>
    <table class="testrail" style="clear: both">
        <caption style="caption-side: top">
            <h2><xsl:value-of select="//run/item[id=$run_id]/name"/></h2>
        </caption>
            <xsl:for-each select="data/results/item">
            <tr>
                <xsl:variable name="test_id" select="test_id"/>
                <td class="number-field">
                    <a href="{//test/item[id=$test_id]/url}">
                        T<xsl:value-of select="test_id"/>
                    </a>
                </td>
                <td class="multiline-field"><xsl:value-of select="//test/item[id=$test_id]/name"/></td>
                <td>
                    <div>
                        <xsl:variable name="status_id" select="status_id"/>
                        <span class="status {//status/item[id=$status_id]/meaning}">
                            <xsl:value-of select="//status/item[id=$status_id]/meaning"/> (Autotest)
                        </span>
                        <dl>
                            <dt class="vms-version">Version</dt>
                            <dd>
                                <xsl:value-of select="version"/>
                            </dd>
                        </dl>
                    </div>
                </td>
                <td>
                    <span style="white-space: pre">
                        <xsl:value-of select="comment"/>
                    </span>
                    <script type="text/javascript">
                        temp1 = document.currentScript.previousElementSibling
                        reg_markdown_url = /\[(.+?)\]\((.+?)\)/g
                        temp1.innerHTML = temp1.textContent.replaceAll(reg_markdown_url, "&lt;a href='$2'&gt;$1&lt;/a&gt;")
                    </script>
                </td>
            </tr>
            </xsl:for-each>
            <xsl:for-each select="//run/item[id=$run_id]/mismatched_tests/item">
            <xsl:variable name="test_id" select="."/>
            <tr class="mismatched">
                <td class="number-field">
                    <a href="{//test/item[id=$test_id]/url}">
                        T<xsl:value-of select="."/>
                    </a>
                </td>
                <td class="multiline-field"><xsl:value-of select="//test/item[id=$test_id]/name"/></td>
            </tr>
            </xsl:for-each>
    </table>
    </xsl:for-each>
    <div class="debug">
        <h2>Unmatched jobs that present in the Batch</h2>
        <table style="margin-left: 5%;">
        <thead>
            <tr>
                <th>FT job</th>
                <th>Status (history)</th>
            </tr>
        </thead>
        <tbody>
        <xsl:for-each select="root/mismatched_jobs">
            <tr>
                <td><a href="{stage_url}"><xsl:value-of select="name"/></a></td>
                <td><a href="{url}"><xsl:value-of select="status"/></a></td>
            </tr>
        </xsl:for-each>
        </tbody>
        </table>
    </div>
</body>
</html>
</xsl:template>
</xsl:stylesheet>