// This is js// peach-blossom.js 
const tgv = (function () {
    // Write as much code as you want here
    dr_cols = {"Sensitive":"#28a745","RR-TB":"#007bff","HR-TB":"#E0ACD5","MDR-TB":"#ffc107","Pre-XDR-TB":"#dc3545","XDR-TB":"#343a40","Other":"#f8f9fa"}
    colour_by_drtype = function(cy){
        cy.nodes().forEach(function(ele, i, eles){
            ele.style('background-color', dr_cols[ele.data('drtype')]);
        })
    }
    add_snp_dists = function(){
        cy.edges().forEach(function(ele, i, eles){
            ele.style('label', document.getElementById('snp_dist_check').checked==true ? ele.data('distance'): "");
        })
    }

    add_sample_labels = function(){
        cy.nodes().forEach(function(ele, i, eles){
            ele.style('label', document.getElementById('sample_name_check').checked==true ? ele.data('id'): "");
        })
    }

    generate_tooltip = function(ele){
        console.log("asd")
        console.log(ele)

        var div = document.createElement('div');
        div.classList.add('popper-div');
        div.innerHTML = ele.data('id') + "<br>" + ele.data('lineage') + "<br>" + ele.data('drtype');
        document.body.appendChild( div );
        return div;
    };

    add_mouseover = function(cy){
        cy.nodes().on('mouseover', function(x){
            ele = x.target
            console.log(ele)
            ele.popper({
                content: function(x){ return generate_tooltip(ele)}
            })
        })

        cy.nodes().on('mouseout', function(x){
            document.getElementsByClassName('popper-div').forEach(function(x){
                x.remove()
            })
        })
    }
    // Return what others can use
    return {
      tgv: function (vars) {
        var gdiv = document.createElement('div');
        gdiv.id = 'cy-div';
        gdiv.style = 'height: 300px; width: 80%; float:right;';
        document.getElementById(vars.div).appendChild(gdiv);
        
        
        cdiv = document.createElement('div');
        cdiv.id = 'cy-controls';
        cdiv.style = 'height: 300px; width: 20%; float:left;';
        
        

        cdiv.innerHTML = `
        <div class="form-check">
            <input class="form-check-input" type="checkbox" value="" id="sample_name_check" onclick="add_sample_labels()">
            <label class="form-check-label" for="sample_name_check">
            Show sample names
            </label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="checkbox" value="" id="snp_dist_check" onclick="add_snp_dists()">
            <label class="form-check-label" for="snp_dist_check">
                Show SNP distance
            </label>
        </div>
        `;
        document.getElementById(vars.div).appendChild(cdiv);
        if (vars.add_controls != true){
            document.getElementById('snp_dist_check').checked = true;
            document.getElementById('sample_name_check').checked = true;
            cdiv.style.display = 'none';
        }
        
        
        cy = cytoscape({

            container: document.getElementById('cy-div'), // container to render in
        
            elements: vars.graph,
        
        
            style: [ // the stylesheet for the graph
                {
                    selector: 'node',
                    style: {
                    'background-color': 'black',
                    // 'label': 'data(id)',
                    'border-width': 2,
                    }
                },
        
                {
                    selector: 'edge',
                    style: {
                    'width': 3,
                    'line-color': '#ccc',
                    'curve-style': 'haystack'
                    }
                }
            ],
        
            layout: {
                name: 'cose'
            },
            hideEdgesOnViewport: true,
            boxSelectionEnabled:true
        
        });
        colour_by_drtype(cy);
        add_snp_dists(cy);
        add_sample_labels(cy);
        add_mouseover(cy);
      }
    }
  })()


